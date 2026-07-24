export default function ProjectInfo() {
  return (
    <div className="project-info">
      <h3>FireWatch Solar</h3>
      <p>
        An interactive map for exploring how wildfire smoke may affect solar power
        plants. It estimates baseline vs smoke-affected generation, a soiling risk
        score (SRI), and a simple bill impact.
      </p>
      <p>
        Covers large solar plants across the Western U.S. (USGS USPVDB). Weather and
        air-quality data drive the site analysis when available.
      </p>
    </div>
  );
}