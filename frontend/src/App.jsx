import './App.css';
import Navbar from './components/Navbar';
import MapContainer from './components/MapContainer';
import { API_BASE } from './config';
import { useState, useEffect, useMemo, useCallback, lazy, Suspense } from 'react';

const InfoPanel = lazy(() => import('./components/InfoPanel'));

function App() {
  const [panelsRaw, setPanelsRaw] = useState([]);
  const [selectedPanelId, setSelectedPanelId] = useState(null);
  const [hoveredPanelId, setHoveredPanelId] = useState(null);
  const [visiblePanels, setVisiblePanels] = useState([]);
  const [selectedDate, setSelectedDate] = useState('2025-07-01');
  const [pendingDate, setPendingDate] = useState('2025-07-01');
  const [navbarOpen, setNavbarOpen] = useState(true);
  const [billDifference, setBillDifference] = useState(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchPanels(attempt = 0) {
      try {
        const panelsRes = await fetch(`${API_BASE}/api/panels`);
        if (!panelsRes.ok) {
          throw new Error(`panels HTTP ${panelsRes.status}`);
        }
        const data = await panelsRes.json();
        const list = Array.isArray(data) ? data : data?.panels || [];
        if (cancelled) return;
        setPanelsRaw(list);
      } catch (err) {
        console.error('Error fetching panels:', err);
        // Backend --reload / cold start can briefly reset connections.
        if (!cancelled && attempt < 4) {
          const delay = 400 * (attempt + 1);
          setTimeout(() => fetchPanels(attempt + 1), delay);
        }
      }
    }
    fetchPanels();
    return () => {
      cancelled = true;
    };
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
    const base = visiblePanels.length > 0 ? visiblePanels : panels;
    if (!selectedPanel) return base;
    if (base.some((p) => p.id === selectedPanel.id)) return base;
    return [...base, selectedPanel];
  }, [visiblePanels, panels, selectedPanel]);

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
        totalCount={panels.length}
      />

      <div className="right-container">
        <MapContainer
          panels={panels}
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
