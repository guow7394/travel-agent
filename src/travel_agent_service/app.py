from fastapi import FastAPI, Request, Response

from .models import PlanBRequest, PlanCityDayRequest, PlanCityDayResponse, TripReviewRequest, TripReviewResponse
from .planner import plan_city_day, replan_for_plan_b
from .review import review_trip
from .static_map import render_mock_static_map_svg


app = FastAPI(
    title="Travel Agent Map Tool",
    version="0.1.0",
    description="Coze-ready one-day city travel planner with AMap integration and mock fallback.",
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "travel-agent-map-tool"}


async def _plan_city_day_from_request(raw_request: Request) -> PlanCityDayResponse:
    payload = {}
    try:
        if raw_request.headers.get("content-length") not in (None, "0"):
            body = await raw_request.json()
            if isinstance(body, dict):
                payload.update(body)
    except ValueError:
        payload = {}

    payload.update(dict(raw_request.query_params))
    hostname = raw_request.url.hostname or ""
    if "public_base_url" not in payload and hostname not in {"testserver", "localhost", "127.0.0.1"}:
        payload["public_base_url"] = str(raw_request.base_url).rstrip("/")
    return plan_city_day(PlanCityDayRequest.model_validate(payload))


@app.post("/plan-city-day", response_model=PlanCityDayResponse)
async def plan_city_day_endpoint(raw_request: Request):
    return await _plan_city_day_from_request(raw_request)


@app.get("/plan-city-day", response_model=PlanCityDayResponse)
async def plan_city_day_get_endpoint(raw_request: Request):
    return await _plan_city_day_from_request(raw_request)


@app.post("/plan-b", response_model=PlanCityDayResponse)
def plan_b_endpoint(request: PlanBRequest):
    return replan_for_plan_b(
        request=request.original_request,
        event=request.event,
        completed_places=request.completed_places,
    )


@app.post("/trip-review", response_model=TripReviewResponse)
def trip_review_endpoint(request: TripReviewRequest):
    return review_trip(request)


@app.get("/mock/static-map.svg")
def mock_static_map(points: str, labels: str = ""):
    svg = render_mock_static_map_svg(points, labels)
    return Response(content=svg, media_type="image/svg+xml")
