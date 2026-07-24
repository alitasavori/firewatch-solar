# FireWatch Solar

Weather and PM2.5 forecasting for PV sites: baseline vs smoke-affected generation and SRI, in a FireWatch-inspired layout. No FIRMS wildfire layers.

Coverage: Western US USGS USPVDB (AZ, CA, CO, ID, MT, NV, NM, OR, UT, WA, WY).

Original projects are **not modified**:

- Upstream forecast app: `../final-project-solarsense/solar-sense`
- FireWatch: `../wildfire-project`

## What this is

| Included | Shell (FireWatch look) | Not included |
| --- | --- | --- |
| Utah EPA panels + MLP/SRI inference | Dark HUD sidebar, Bungee/Rajdhani, cyan/gold chrome | NASA FIRMS / live wildfire layers |
| Generation bars (baseline vs smoke-affected) | Satellite-streets Mapbox basemap | HSU fire-risk FireWatch product tools |
| SRI dial + sparkline, bill difference | Angled panel / clip-path styling | Extra FireWatch-only agents |
| Western US PV inventory on map/list | | Fake EPA IDs for non-Utah plants |

## Coverage scope

Map/list inventory = **Western US USGS USPVDB** (AZ, CA, CO, ID, MT, NV, NM, OR, UT, WA, WY) — the fullest PV set FireWatch uses — **plus** Utah EPA monitoring sites.

This is **not full CONUS**.

### Inference behavior

| Site type | On map/list | MLP / weather / SRI |
| --- | --- | --- |
| Utah EPA (county + site IDs) | Yes | Full (`/api/panel/data`, `/api/panel/sri`) |
| Western US USPVDB | Yes | Nearest EPA PM2.5 or Open-Meteo when available; otherwise map-only |

Utah USPVDB plants within ~2.5 km of a Utah EPA site are deduped in favor of the inference-capable record.

## Ports (avoid conflicts)

| Service | Port | URL |
| --- | --- | --- |
| Hybrid backend | **8002** | http://127.0.0.1:8002 |
| Hybrid frontend (production preview) | **3002** | http://127.0.0.1:3002 |
| (Original forecast app often) | 8000 / 3000 | — |
| (Original FireWatch often) | 8001 / … | — |

Useful API checks:

- http://127.0.0.1:8002/api/health
- http://127.0.0.1:8002/api/panels
- http://127.0.0.1:8002/api/panels/meta

## Quick start

```powershell
git clone https://github.com/alitasavori/firewatch-solar.git
cd firewatch-solar

# backend on :8002
cd backend; python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8002

# frontend on :3002 (new terminal)
cd frontend; npm install; Copy-Item .env.example .env   # add your Mapbox token
npm run build; npm run preview
```

## How to run

### Backend

```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8002 --reload
```

First `/api/panels` call may fetch USPVDB (cached to `uspvdb_western_cache.json` for 24h).

### Frontend (recommended: production build)

```powershell
cd frontend
npm install
npm run build
npm run preview
```

Open http://127.0.0.1:3002

Dev server (slower HMR with Mapbox):

```powershell
npm run dev
```

### Environment

A Mapbox token is **required** for the satellite basemap. Copy the example file and add your own:

```powershell
cd frontend
Copy-Item .env.example .env
```

`frontend/.env`:

```
VITE_API_URL=http://127.0.0.1:8002
VITE_MAPBOX_TOKEN=pk.your_mapbox_token_here
```

Free tokens: https://account.mapbox.com/access-tokens/

`.env` is gitignored, so a real token never lands in version control.

## Layout

```
solarsense-firewatch-shell/
  backend/          # FastAPI + MLP models + USPVDB merge
  frontend/         # Vite React + FireWatch shell styling
  README.md
```
