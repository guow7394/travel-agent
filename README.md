# Travel Agent MVP

Coze-ready travel planning MVP for a hackathon demo. The repo contains a lightweight map tool service plus Coze configuration artifacts.

## What It Does

- Plans a one-day city route from candidate places.
- Falls back to deterministic Shanghai mock data when `AMAP_WEB_SERVICE_KEY` is missing.
- Uses AMap Web Service for geocoding, walking/transit/driving route durations, nearby restaurant POIs, and static maps when configured.
- Returns route order, legs, distance, time, food recommendations, budget ledger, feasibility warnings, conflict resolution, a static map URL, and a Markdown action card.
- Supports PlanB replanning and post-trip review/profile updates.

## Run Locally

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/uvicorn travel_agent_service.app:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

Example plan:

```bash
curl -s http://localhost:8000/plan-city-day \
  -H 'Content-Type: application/json' \
  -d '{
    "city":"上海",
    "date":"2026-05-23",
    "start_time":"09:30",
    "end_time":"20:00",
    "budget_total_cny":500,
    "people_count":2,
    "mode":"balanced",
    "start_place":"人民广场",
    "end_place":"人民广场",
    "candidate_places":["上海博物馆","豫园","外滩","武康路"],
    "traveler_preferences":[
      {"name":"A","likes":["拍照","美食"],"constraints":["少走路"]},
      {"name":"B","likes":["博物馆","高性价比"],"constraints":[]}
    ]
  }'
```

## Coze Setup

1. Deploy this service to an HTTPS host.
2. Set `PUBLIC_BASE_URL` to the deployed host.
3. Optional: set `AMAP_WEB_SERVICE_KEY` after creating a 高德 Web 服务 Key.
4. In Coze, create a custom plugin from [coze/openapi.yaml](coze/openapi.yaml).
5. Use [coze/agent_prompt.md](coze/agent_prompt.md) as the main Agent prompt.
6. Build the four workflows described in [coze/workflows.md](coze/workflows.md).
7. Use [coze/demo_script.md](coze/demo_script.md) for the hackathon demo flow.

## Deploy to Vercel

Vercel can deploy FastAPI directly when the project root exports a `FastAPI` instance from `app.py`.

1. Install Vercel CLI:

```bash
npm i -g vercel
```

2. Log in:

```bash
vercel login
```

3. Deploy from this repo root:

```bash
vercel
```

When Vercel asks questions, use these defaults:

- Set up and deploy: `Y`
- Link to existing project: `N`
- Project name: `travel-agent`
- Directory: `./`
- Override settings: `N`

4. Add environment variables in the Vercel dashboard:

```text
AMAP_WEB_SERVICE_KEY=your_amap_web_service_key
TRAVEL_AGENT_LIVE_DISTANCE=true
PUBLIC_BASE_URL=https://your-vercel-domain.vercel.app
```

`TRAVEL_AGENT_LIVE_DISTANCE=true` enables live AMap walking, transit, and driving route calls plus nearby restaurant POI search. If any AMap call fails or times out, the service keeps returning a complete plan using deterministic fallback estimates.

5. Redeploy production:

```bash
vercel --prod
```

After deployment, verify:

```bash
curl https://your-vercel-domain.vercel.app/health
```

Then update `coze/openapi.yaml`:

```yaml
servers:
  - url: https://your-vercel-domain.vercel.app
```

## Test

```bash
.venv/bin/python -m pytest -q
```

## Deployment Notes

The service is a normal FastAPI app:

```bash
uvicorn travel_agent_service.app:app --host 0.0.0.0 --port "${PORT:-8000}"
```

For Coze, the endpoint must be reachable over HTTPS. If no AMap key is configured, `static_map_url` points to `/mock/static-map.svg` on the same service, so `PUBLIC_BASE_URL` must be the public HTTPS origin.
