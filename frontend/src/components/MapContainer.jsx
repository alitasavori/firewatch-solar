import { useState, useRef, useEffect, useCallback, useMemo, memo } from 'react';
import MapboxMap, { Marker as MapboxMarker, Source } from 'react-map-gl';
import MapLibreMap, { Marker as MapLibreMarker } from 'react-map-gl/maplibre';
import 'mapbox-gl/dist/mapbox-gl.css';
import 'maplibre-gl/dist/maplibre-gl.css';
import '../styles/MapContainer.css';
import { MAPBOX_TOKEN } from '../config';

const USE_MAPBOX = Boolean(MAPBOX_TOKEN);
const ReactMapGl = USE_MAPBOX ? MapboxMap : MapLibreMap;
const Marker = USE_MAPBOX ? MapboxMarker : MapLibreMarker;

// Free OSM raster style — used only when no Mapbox token is configured.
const OSM_STYLE = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [{ id: 'osm', type: 'raster', source: 'osm' }],
};

const MAPBOX_STYLE = 'mapbox://styles/mapbox/satellite-streets-v12';

const WEST_BOUNDS = [
  [-125.5, 30.5],
  [-102.0, 49.5],
];

const INITIAL_VIEW = {
  longitude: -114.0,
  latitude: 40.0,
  zoom: 4.6,
};

const PanelMarker = memo(function PanelMarker({
  panel,
  isSelected,
  isHovered,
  onPanelClick,
  onHoverPanel,
}) {
  const cap = panel.capacityMw || 1.5;
  const norm = Math.max(0, Math.min(1, (cap - 1.5) / (80 - 1.5)));
  const baseColor = panel.inferenceCapable
    ? `rgb(255, ${Math.round(255 - 75 * norm)}, ${Math.round(150 - 150 * norm)})`
    : `rgb(${Math.round(0 + 40 * norm)}, ${Math.round(180 + 40 * norm)}, 255)`;

  const markerColor = isSelected
    ? 'rgb(255, 80, 80)'
    : isHovered
      ? 'rgb(255, 255, 120)'
      : baseColor;

  return (
    <Marker longitude={panel.longitude} latitude={panel.latitude}>
      <button
        style={{
          background: markerColor,
          border: isHovered
            ? '2px solid #ffc800'
            : panel.inferenceCapable
              ? '1px solid #ffc800'
              : '1px solid #00d4ff',
          borderRadius: '50%',
          width: isSelected ? 18 : panel.inferenceCapable ? 14 : 10,
          height: isSelected ? 18 : panel.inferenceCapable ? 14 : 10,
          cursor: 'pointer',
          boxShadow: isHovered ? '0 0 8px rgba(255,200,0,0.8)' : 'none',
          padding: 0,
        }}
        onClick={() => onPanelClick(panel.id)}
        onMouseEnter={() => onHoverPanel(panel.id)}
        onMouseLeave={() => onHoverPanel(null)}
        aria-label={panel.name}
        title={`${panel.name} (${panel.capacity})${
          panel.inferenceCapable
            ? panel.pm25Source === 'epa_nearest'
              ? ` · EPA PM2.5 ~${panel.pm25DistanceKm ?? '?'} km`
              : panel.pm25Source === 'openmeteo'
                ? ' · Open-Meteo PM2.5'
                : ''
            : ' · map only'
        }`}
      />
    </Marker>
  );
});

export default function MapContainer({
  panels,
  selectedPanelId,
  hoveredPanelId,
  onPanelClick,
  onHoverPanel,
  navbarOpen,
  onVisiblePanelsChange,
  pendingDate,
  setPendingDate,
  selectedDate,
  setSelectedDate,
}) {
  const mapRef = useRef(null);
  const [zoom, setZoom] = useState(INITIAL_VIEW.zoom);
  const [infoOpen, setInfoOpen] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const onVisibleRef = useRef(onVisiblePanelsChange);
  onVisibleRef.current = onVisiblePanelsChange;

  const recalcVisible = useCallback(() => {
    const map = mapRef.current?.getMap?.();
    if (!map) return;
    const bounds = map.getBounds();
    const visible = panels.filter(
      (p) =>
        p.latitude <= bounds._ne.lat &&
        p.latitude >= bounds._sw.lat &&
        p.longitude <= bounds._ne.lng &&
        p.longitude >= bounds._sw.lng
    );
    onVisibleRef.current?.(visible);
  }, [panels]);

  useEffect(() => {
    if (!mapReady) return;
    const map = mapRef.current?.getMap?.();
    if (!map) return;

    const onMoveEnd = () => {
      setZoom(map.getZoom());
      recalcVisible();
    };

    recalcVisible();
    map.on('moveend', onMoveEnd);
    map.on('zoomend', onMoveEnd);
    return () => {
      map.off('moveend', onMoveEnd);
      map.off('zoomend', onMoveEnd);
    };
  }, [mapReady, recalcVisible]);

  useEffect(() => {
    const map = mapRef.current?.getMap?.();
    if (!map) return;
    const t = setTimeout(() => {
      map.resize();
      recalcVisible();
    }, 300);
    return () => clearTimeout(t);
  }, [navbarOpen, selectedPanelId, recalcVisible]);

  const renderPanels = useMemo(() => {
    if (panels.length <= 600 || zoom >= 6.5) return panels;
    return [...panels]
      .sort((a, b) => {
        const ai = a.inferenceCapable ? 1 : 0;
        const bi = b.inferenceCapable ? 1 : 0;
        if (bi !== ai) return bi - ai;
        return (b.capacityMw || 0) - (a.capacityMw || 0);
      })
      .slice(0, 600);
  }, [panels, zoom]);

  const flyTo = (opts) => {
    const map = mapRef.current?.getMap?.();
    if (!map) return;
    map.easeTo({ ...opts, duration: 400 });
  };

  const mapProps = USE_MAPBOX
    ? {
        mapStyle: MAPBOX_STYLE,
        mapboxAccessToken: MAPBOX_TOKEN,
        terrain: { source: 'mapbox-dem', exaggeration: 1.2 },
      }
    : {
        mapStyle: OSM_STYLE,
      };

  return (
    <div className="mapbox-container">
      <ReactMapGl
        ref={mapRef}
        initialViewState={INITIAL_VIEW}
        onLoad={() => setMapReady(true)}
        style={{ width: '100%', height: '100%' }}
        maxBounds={WEST_BOUNDS}
        reuseMaps
        {...mapProps}
      >
        {USE_MAPBOX && (
          <Source
            id="mapbox-dem"
            type="raster-dem"
            url="mapbox://mapbox.mapbox-terrain-dem-v1"
            tileSize={512}
            maxzoom={14}
          />
        )}

        {renderPanels.map((panel) => (
          <PanelMarker
            key={panel.id}
            panel={panel}
            isSelected={panel.id === selectedPanelId}
            isHovered={panel.id === hoveredPanelId}
            onPanelClick={onPanelClick}
            onHoverPanel={onHoverPanel}
          />
        ))}

        <div className="map-info-button" onClick={() => setInfoOpen(true)}>
          <span>i</span>
        </div>

        {infoOpen && (
          <div className="map-info-panel">
            <button className="close-btn" onClick={() => setInfoOpen(false)}>
              ×
            </button>
            <h3>Legend</h3>
            <p>
              <span className="legend-dot inference" /> Utah EPA sites (MLP/SRI ready)
            </p>
            <p>
              <span className="legend-dot uspvdb" /> Western US USPVDB (nearest EPA or Open-Meteo AQ)
            </p>
            <p className="muted">
              Zoom in to see more markers. FIRMS / wildfire layers are intentionally omitted.
              PM2.5 uses the nearest EPA monitor within 100 km when available; otherwise Open-Meteo.
            </p>
          </div>
        )}

        <div className="map-zoom-controls">
          <button
            onClick={() =>
              flyTo({
                center: [INITIAL_VIEW.longitude, INITIAL_VIEW.latitude],
                zoom: INITIAL_VIEW.zoom,
              })
            }
            title="Full Western extent"
          >
            <span>⌂</span>
          </button>
          <button
            onClick={() => {
              const map = mapRef.current?.getMap?.();
              if (map) flyTo({ zoom: map.getZoom() + 0.5 });
            }}
          >
            <span>+</span>
          </button>
          <button
            onClick={() => {
              const map = mapRef.current?.getMap?.();
              if (map) flyTo({ zoom: map.getZoom() - 0.5 });
            }}
          >
            <span>−</span>
          </button>
        </div>

        <div className="map-date-control">
          <div className="map-date-inner">
            <input
              type="date"
              required
              min="2017-01-01"
              max="2025-07-01"
              value={pendingDate}
              onChange={(e) => setPendingDate(e.target.value)}
            />
            <button
              className="apply-date-btn"
              disabled={!pendingDate || pendingDate === selectedDate}
              onClick={() => setSelectedDate(pendingDate)}
            >
              Apply Date
            </button>
          </div>
        </div>
      </ReactMapGl>
    </div>
  );
}
