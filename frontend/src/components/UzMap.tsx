import "leaflet/dist/leaflet.css";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";
import type { Num } from "@/lib/types";
import { toNum } from "@/lib/format";

export interface MapPoint { id: number; name: string; lat: Num; lng: Num; value: number; label: string; selected?: boolean }

/** Region-level map of Uzbekistan. Markers sit on approximate regional centres — never on
 *  invented supplier coordinates. Size is proportional to `value`. */
export function UzMap({ points, onSelect, height = 420 }: { points: MapPoint[]; onSelect?: (id: number) => void; height?: number }) {
  const max = Math.max(1, ...points.map((p) => p.value));
  return (
    <div className="overflow-hidden rounded-lg border border-border" style={{ height }}>
      <MapContainer center={[41.4, 64.6]} zoom={6} minZoom={5} maxZoom={10} scrollWheelZoom={false} style={{ height: "100%", width: "100%" }}
        maxBounds={[[36.5, 55.0], [46.0, 74.5]]}>
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        {points.filter((p) => toNum(p.lat) !== null && toNum(p.lng) !== null).map((p) => (
          <CircleMarker key={p.id} center={[toNum(p.lat)!, toNum(p.lng)!]} radius={6 + 22 * Math.sqrt(p.value / max)}
            pathOptions={{ color: p.selected ? "#b45309" : "#0f766e", fillColor: p.selected ? "#f59e0b" : "#14b8a6",
              fillOpacity: p.value ? 0.55 : 0.12, weight: p.selected ? 3 : 1.5 }}
            eventHandlers={{ click: () => onSelect?.(p.id) }}>
            <Tooltip direction="top"><div className="text-xs"><b>{p.name}</b><br />{p.label}</div></Tooltip>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
