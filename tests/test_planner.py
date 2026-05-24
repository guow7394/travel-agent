from travel_agent_service.amap import AmapRoute
from travel_agent_service.models import FoodRecommendation, Location, PlanCityDayRequest, TravelerPreference
from travel_agent_service.planner import plan_city_day


def test_mock_planner_orders_shanghai_places_by_route_shape():
    request = PlanCityDayRequest(
        city="上海",
        date="2026-05-23",
        start_time="09:30",
        end_time="20:00",
        budget_total_cny=500,
        people_count=2,
        mode="balanced",
        start_place="人民广场",
        end_place="人民广场",
        candidate_places=["武康路", "外滩", "上海博物馆", "豫园"],
        traveler_preferences=[
            TravelerPreference(name="A", likes=["拍照"], constraints=["少走路"]),
            TravelerPreference(name="B", likes=["博物馆"], constraints=[]),
        ],
    )

    result = plan_city_day(request)

    assert [stop.name for stop in result.route] == ["上海博物馆", "豫园", "外滩", "武康路"]
    assert result.legs[1].transport in {"taxi", "metro", "walk"}
    assert result.mocked is True
    assert result.feasibility.status == "ok"


def test_live_amap_routes_and_food_are_used_when_enabled(monkeypatch):
    class FakeAmapClient:
        key = "test-key"
        enabled = True

        def geocode(self, address, city):
            return None

        def route(self, origin, destination, transport, city):
            durations = {"walk": 6, "metro": 18, "taxi": 11}
            distances = {"walk": 500, "metro": 3200, "taxi": 2800}
            return AmapRoute(
                distance_m=distances.get(transport, 1000),
                duration_min=durations.get(transport, 12),
            )

        def distance(self, origin, destination):
            return None

        def search_food_near(self, location, near_stop, city, per_person_budget):
            return [
                FoodRecommendation(
                    name="高德真实餐厅",
                    near_stop=near_stop,
                    avg_price_cny=42,
                    location=Location(longitude=location.longitude + 0.001, latitude=location.latitude),
                    reason="高德周边餐饮POI，适合作为顺路用餐点。",
                )
            ]

    monkeypatch.setenv("TRAVEL_AGENT_LIVE_DISTANCE", "true")
    monkeypatch.setattr("travel_agent_service.planner.AmapClient", FakeAmapClient)

    request = PlanCityDayRequest(
        city="上海",
        date="2026-05-23",
        start_time="09:30",
        end_time="20:00",
        budget_total_cny=500,
        people_count=2,
        mode="low_budget",
        start_place="人民广场",
        end_place="人民广场",
        candidate_places=["上海博物馆", "豫园", "外滩", "武康路"],
    )

    result = plan_city_day(request)

    assert result.mocked is False
    assert result.legs[1].transport == "metro"
    assert result.legs[1].duration_min == 18
    assert result.food_recommendations[0].name == "高德真实餐厅"
    assert result.static_map_url.startswith("https://restapi.amap.com/v3/staticmap")


def test_live_amap_failures_fall_back_to_estimates(monkeypatch):
    class FailingAmapClient:
        key = "test-key"
        enabled = True

        def geocode(self, address, city):
            return None

        def route(self, origin, destination, transport, city):
            return None

        def distance(self, origin, destination):
            return None

        def search_food_near(self, location, near_stop, city, per_person_budget):
            return []

    monkeypatch.setenv("TRAVEL_AGENT_LIVE_DISTANCE", "true")
    monkeypatch.setattr("travel_agent_service.planner.AmapClient", FailingAmapClient)

    request = PlanCityDayRequest(
        city="上海",
        date="2026-05-23",
        start_time="09:30",
        end_time="20:00",
        budget_total_cny=500,
        people_count=2,
        mode="balanced",
        start_place="人民广场",
        end_place="人民广场",
        candidate_places=["上海博物馆", "豫园", "外滩", "武康路"],
    )

    result = plan_city_day(request)

    assert result.mocked is True
    assert result.legs[0].duration_min > 0
    assert result.food_recommendations[0].name in {"大壶春", "老盛昌汤包馆"}
    assert any("高德路径规划暂不可用" in warning for warning in result.feasibility.warnings)
