/**
 * API base for hybrid backend (default port 8002).
 * Override with VITE_API_URL in .env
 */
export const API_BASE =
  import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : 'http://127.0.0.1:8002';

/**
 * Mapbox access token. Required for the satellite basemap to render.
 * Set VITE_MAPBOX_TOKEN in frontend/.env (copy from .env.example).
 */
export const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || '';

if (!MAPBOX_TOKEN) {
  console.warn(
    'Missing VITE_MAPBOX_TOKEN: the basemap will not render. Copy frontend/.env.example to frontend/.env and add a Mapbox token.'
  );
}