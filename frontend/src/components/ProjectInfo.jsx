export default function ProjectInfo({ coverageMeta }) {
  return (
    <div className="project-info">
      <h3>FireWatch Solar</h3>
      <p>
        Weather and PM2.5 forecasting for PV sites: baseline vs smoke-affected
        generation and SRI, in a FireWatch-inspired layout. No FIRMS wildfire layers.
      </p>
      <p>
        Coverage:{' '}
        {coverageMeta?.coverage ||
          'Western US USGS USPVDB + Utah EPA monitoring sites'}
        . Not full CONUS.
      </p>
      <p>
        Sites without a resolved PM2.5 source appear on the map/list only; MLP/SRI
        is not invented for those plants.
      </p>
    </div>
  );
}
