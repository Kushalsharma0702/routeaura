import { useEffect } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet';

export interface MapStop { id: string; name: string; lat: number; lng: number; label?: string }
export interface MapRoute { key: string; color: string; dashed?: boolean; stops: MapStop[]; title: string }

const numbered = (n: string, color: string) => L.divIcon({
  className: '', html: `<div style="background:${color};color:#fff;width:26px;height:26px;border-radius:50%;display:flex;align-items:center;justify-content:center;font:600 12px system-ui;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4)">${n}</div>`,
  iconSize: [26, 26], iconAnchor: [13, 13],
});

function FitBounds({ points }: { points: [number, number][] }) {
  const map = useMap();
  useEffect(() => { if (points.length) map.fitBounds(points, { padding: [30, 30], maxZoom: 15 }); }, [map, points]);
  return null;
}

/**
 * Route map. Straight lines join consecutive stops in visiting order: they show ORDER, not roads. Real road
 * geometry would need a routing provider that returns polylines (not integrated yet).
 */
export default function ItineraryMap({ routes, start, height = 360 }: { routes: MapRoute[]; start?: { lat: number; lng: number; name: string }; height?: number }) {
  const all: [number, number][] = [...(start ? [[start.lat, start.lng] as [number, number]] : []), ...routes.flatMap(r => r.stops.map(s => [s.lat, s.lng] as [number, number]))];
  const centre: [number, number] = all[0] ?? [26.9, 75.8];
  return (
    <div className="rounded-xl overflow-hidden border border-border/50" style={{ height }} role="region" aria-label="Itinerary map" data-testid="itinerary-map">
      <MapContainer center={centre} zoom={12} style={{ height: '100%', width: '100%' }} scrollWheelZoom={false}>
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <FitBounds points={all} />
        {start && <Marker position={[start.lat, start.lng]} icon={numbered('S', '#334155')}><Popup>Start: {start.name}</Popup></Marker>}
        {routes.map(r => (
          <div key={r.key}>
            <Polyline positions={[...(start ? [[start.lat, start.lng] as [number, number]] : []), ...r.stops.map(s => [s.lat, s.lng] as [number, number])]}
              pathOptions={{ color: r.color, weight: 4, opacity: r.dashed ? 0.55 : 0.9, dashArray: r.dashed ? '8 8' : undefined }} />
            {!r.dashed && r.stops.map((s, i) => (
              <Marker key={s.id} position={[s.lat, s.lng]} icon={numbered(s.label ?? String(i + 1), r.color)}><Popup><strong>{s.name}</strong><br />{r.title}, stop {i + 1}</Popup></Marker>
            ))}
          </div>
        ))}
      </MapContainer>
    </div>
  );
}
