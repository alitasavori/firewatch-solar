import './App.css';
import Navbar from './components/Navbar';
import MapContainer from './components/MapContainer';
import { API_BASE } from './config';
import { useState, useEffect, useMemo, useCallback, lazy, Suspense } from 'react';

const InfoPanel = lazy(() => import('./components/InfoPanel'));

function App() {
  const [panelsRaw, setPanelsRaw] = useState([]);
  const [coverageMeta, setCoverageMeta] = useState(null);
  const [selectedPanelId, setSelectedPanelId] = useState(null);
  const [hoveredPanelId, setHoveredPanelId] = useState(null);
  const [visiblePanels, setVisiblePanels] = useState([]);
  const [selectedDate, setSelectedDate] = useState('2025-07-01');
  const [pendingDate, setPendingDate] = useState('2025-07-01');
  const [navbarOpen, setNavbarOpen] = useState(true);
  const [billDifference, setBillDifference] = useState(null);
  const [listFilter, setListFilter] = useState('all'); // all | inference | map

  useEffect(() => {
    async function fetchPanels() {
      try {
        const [panelsRes, metaRes] = await Promise.all([
          fetch(`${API_BASE}/api/panels`),
          fetch(`${API_BASE}/api/panels/meta`).catch(() => null),
        ]);
        const data = await panelsRes.json();
        setPanelsRaw(Array.isArray(data) ? data : data?.panels || []);
        if (metaRes?.ok) {
          setCoverageMeta(await metaRes.json());
        }
      } catch (err) {
        console.error('Error fetching panels:', err);
      }
    }
    fetchPanels();
  }, []);

  const panels = useMemo(() => {
    return panelsRaw.map((p) => ({
      id: p.panel_id || `${p.county || ''}${p.site || ''}`,
      name: p.site_name,
      county: p.county_name,
      number: p.site || p.case_id || '—',
      location: p.state
        ? `${p.county_name || '—'}, ${p.state}`
        : `${p.county_name || '—'} County`,
      capacity: `${p.capacity} MW`,
      capacityMw: Number(p.capacity) || 0,
      latitude: Number(p.latitude),
      longitude: Number(p.longitude),
      inferenceCapable: Boolean(p.inference_capable),
      source: p.source || 'solarsense',
      state: p.state || '',
      note: p.note || '',
      pm25Source: p.pm25_source || '',
      pm25MonitorName: p.pm25_monitor_name || '',
      pm25DistanceKm: p.pm25_distance_km,
      yearOnline: p.year_online,
      raw: p,
    }));
  }, [panelsRaw]);

  const filteredPanels = useMemo(() => {
    if (listFilter === 'inference') return panels.filter((p) => p.inferenceCapable);
    if (listFilter === 'map') return panels.filter((p) => !p.inferenceCapable);
    return panels;
  }, [panels, listFilter]);

  const selectedPanel = useMemo(
    () => panels.find((p) => p.id === selectedPanelId) || null,
    [panels, selectedPanelId]
  );

  const handleVisiblePanelsChange = useCallback((visible) => {
    setVisiblePanels((prev) => {
      if (
        prev.length === visible.length &&
        prev.every((p, i) => p.id === visible[i]?.id)
      ) {
        return prev;
      }
      return visible;
    });
  }, []);

  const panelsToShow = useMemo(() => {
    const base = visiblePanels.length > 0 ? visiblePanels : filteredPanels;
    const scoped = base.filter((p) => {
      if (listFilter === 'inference') return p.inferenceCapable;
      if (listFilter === 'map') return !p.inferenceCapable;
      return true;
    });
    if (!selectedPanel) return scoped;
    if (scoped.some((p) => p.id === selectedPanel.id)) return scoped;
    return [...scoped, selectedPanel];
  }, [visiblePanels, filteredPanels, selectedPanel, listFilter]);

  return (
    <div className="app-container">
      <Navbar
        className={navbarOpen ? '' : 'collapsed'}
        collapseNavbar={() => setNavbarOpen(false)}
        panels={panelsToShow}
        selectedPanelId={selectedPanelId}
        hoveredPanelId={hoveredPanelId}
        onSelectPanel={setSelectedPanelId}
        onHoverPanel={setHoveredPanelId}
        billDifference={billDifference}
        coverageMeta={coverageMeta}
        listFilter={listFilter}
        setListFilter={setListFilter}
        totalCount={panels.length}
      />

      <div className="right-container">
        <div className="fw-hud-title">
          <span>FIREWATCH SOLAR</span>
        </div>

        <MapContainer
          panels={filteredPanels}
          selectedPanelId={selectedPanelId}
          hoveredPanelId={hoveredPanelId}
          onPanelClick={setSelectedPanelId}
          onHoverPanel={setHoveredPanelId}
          onVisiblePanelsChange={handleVisiblePanelsChange}
          navbarOpen={navbarOpen}
          pendingDate={pendingDate}
          setPendingDate={setPendingDate}
          setSelectedDate={setSelectedDate}
          selectedDate={selectedDate}
        />

        {!navbarOpen && (
          <div className="overlay-logo" onClick={() => setNavbarOpen(true)}>
            <span className="fw-logo-mark">FIREWATCH SOLAR</span>
          </div>
        )}

        <Suspense
          fallback={
            <div className="info-panel">Loading forecast panel…</div>
          }
        >
          <InfoPanel
            panel={selectedPanel}
            selectedPanel={selectedPanelId}
            startDate={selectedDate}
            onBillDifferenceComputed={setBillDifference}
          />
        </Suspense>
      </div>
    </div>
  );
}

export default App;
