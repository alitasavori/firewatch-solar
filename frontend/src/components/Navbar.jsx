import PanelList from './PanelList';
import ProjectInfo from './ProjectInfo';
import '../styles/Navbar.css';

export default function Navbar({
  className,
  collapseNavbar,
  panels = [],
  selectedPanelId,
  hoveredPanelId,
  onSelectPanel,
  onHoverPanel,
  billDifference,
  listFilter,
  setListFilter,
  totalCount,
}) {
  return (
    <div className={`navbar ${className || ''}`}>
      <div className="navbar-brand" onClick={collapseNavbar} title="Collapse sidebar">
        <h1 className="fw-logo">FIREWATCH SOLAR</h1>
        <p className="fw-tagline">PV smoke impact forecast</p>
      </div>

      <div className="fw-badge-live">Map live</div>

      <div className="fw-stat-box">
        <div>
          Sites loaded: <b>{totalCount ?? panels.length}</b>
        </div>
      </div>

      <div className="fw-filter-row">
        <button
          type="button"
          className={listFilter === 'all' ? 'is-active' : ''}
          onClick={() => setListFilter('all')}
        >
          All
        </button>
        <button
          type="button"
          className={listFilter === 'inference' ? 'is-active' : ''}
          onClick={() => setListFilter('inference')}
        >
          MLP ready
        </button>
        <button
          type="button"
          className={listFilter === 'map' ? 'is-active' : ''}
          onClick={() => setListFilter('map')}
        >
          Map only
        </button>
      </div>

      <div className="navbar-section">
        <PanelList
          panels={panels}
          selectedPanelId={selectedPanelId}
          hoveredPanelId={hoveredPanelId}
          onSelect={onSelectPanel}
          onHoverChange={onHoverPanel}
          billDifference={billDifference}
        />
      </div>

      <div className="navbar-info">
        <ProjectInfo />
      </div>
    </div>
  );
}