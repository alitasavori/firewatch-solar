import '../styles/PanelList.css';

export default function PanelList({
  panels,
  selectedPanelId,
  hoveredPanelId,
  onSelect,
  onHoverChange,
  billDifference,
}) {
  return (
    <div className="panel-list">
      <div className="panel-list__header">
        <div>Site Name</div>
        <div>ID</div>
        <div>Location</div>
        <div>Capacity</div>
      </div>

      <div className="panel-list__body">
        {Array.isArray(panels) && panels.length > 0 ? (
          panels.map((p) => {
            const isSelected = p.id === selectedPanelId;
            const isHovered = p.id === hoveredPanelId;

            return (
              <button
                key={p.id}
                className={[
                  'panel-list__row',
                  isSelected ? 'is-selected' : '',
                  isHovered ? 'is-hovered' : '',
                  p.inferenceCapable ? 'is-inference' : 'is-map-only',
                ].join(' ')}
                onClick={() => onSelect?.(p.id)}
                onMouseEnter={() => onHoverChange?.(p.id)}
                onMouseLeave={() => onHoverChange?.(null)}
                title={p.name}
                type="button"
              >
                <div className="panel-card__title">
                  <span className="panel-list__cell" style={{ minWidth: 0 }}>
                    {p.name ?? '—'}
                  </span>
                  <span className="panel-card__capacity" title="Capacity (MW)">
                    {p.capacity ?? '—'}
                  </span>
                </div>

                <div className="panel-card__subtitle">
                  {p.inferenceCapable
                    ? p.pm25Source === 'epa_nearest'
                      ? `MLP/SRI · EPA ~${p.pm25DistanceKm ?? '?'} km`
                      : p.pm25Source === 'openmeteo'
                        ? 'MLP/SRI · Open-Meteo AQ'
                        : 'MLP / SRI ready'
                    : 'Map only · no AQ source'}
                  {' · '}
                  #{p.number ?? '—'}
                </div>

                <div className="panel-card__meta">
                  <span className="panel-card__meta-item">
                    <span className="panel-card__meta-label">Loc:</span>
                    <span className="panel-list__cell">{p.location ?? '—'}</span>
                  </span>
                </div>

                {isSelected && billDifference != null && p.inferenceCapable && (
                  <div className="panel-card__bill-diff">
                    Monthly Electricity Difference: $
                    {billDifference.toLocaleString(undefined, {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </div>
                )}

                <div className="panel-list__cell">{p.name ?? '—'}</div>
                <div className="panel-list__cell">{p.number ?? '—'}</div>
                <div className="panel-list__cell">{p.location ?? '—'}</div>
                <div className="panel-list__cell">{p.capacity ?? '—'}</div>
              </button>
            );
          })
        ) : (
          <div className="panel-list__empty">No panels in view. Zoom/pan the map or change filter.</div>
        )}
      </div>
    </div>
  );
}
