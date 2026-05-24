from fastapi.testclient import TestClient

from travel_agent_service.app import app


client = TestClient(app)


def sample_payload(**overrides):
    payload = {
        "city": "上海",
        "date": "2026-05-23",
        "start_time": "09:30",
        "end_time": "20:00",
        "budget_total_cny": 500,
        "people_count": 2,
        "mode": "balanced",
        "start_place": "人民广场",
        "end_place": "人民广场",
        "candidate_places": ["上海博物馆", "豫园", "外滩", "武康路"],
        "traveler_preferences": [
            {"name": "A", "likes": ["拍照", "美食"], "constraints": ["少走路"]},
            {"name": "B", "likes": ["博物馆", "高性价比"], "constraints": []},
        ],
    }
    payload.update(overrides)
    return payload


def test_plan_city_day_returns_mock_route_budget_and_action_card_without_amap_key():
    response = client.post("/plan-city-day", json=sample_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["mocked"] is True
    assert [stop["name"] for stop in body["route"]][:2] == ["上海博物馆", "豫园"]
    assert body["legs"][0]["from"] == "人民广场"
    assert body["budget_ledger"]["planned_total"] <= 500
    assert body["feasibility"]["status"] in {"ok", "adjusted"}
    assert body["static_map_url"].startswith("http://localhost:8000/mock/static-map.svg")
    assert "## 今日行动卡" in body["action_card_markdown"]
    assert "PlanB触发条件" in body["action_card_markdown"]


def test_plan_city_day_accepts_coze_friendly_string_payload_with_defaults():
    response = client.post(
        "/plan-city-day",
        json={
            "city": "上海",
            "date": "2026-05-23",
            "budgettotalcny": "160",
            "peoplecount": "2",
            "mode": "low_budget",
            "candidateplaces": "上海博物馆, 豫园, 外滩, 武康路",
            "travelerpreferences": '[{"name":"A","likes":["拍照","美食"],"constraints":["少走路"]}]',
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [stop["name"] for stop in body["route"]][:3] == ["上海博物馆", "豫园", "外滩"]
    assert body["mode"] == "low_budget"
    assert body["legs"][0]["from"] == "人民广场"
    assert body["budget_ledger"]["risk"] in {"tight", "over"}


def test_plan_city_day_accepts_coze_query_parameter_drift():
    response = client.post(
        "/plan-city-day?candidateplacescandidateplaces=上海博物馆,豫园,外滩,武康路",
        json={
            "city": "上海",
            "date": "2026-05-23",
            "budgettotalcny": "500",
            "peoplecount": "2",
            "mode": "low_budget",
            "travelerpreferences": '[{"name":"A","likes":["拍照"],"constraints":["少走路"]}]',
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [stop["name"] for stop in body["route"]][:2] == ["上海博物馆", "豫园"]
    assert body["mode"] == "low_budget"


def test_plan_city_day_accepts_coze_get_query_request():
    response = client.get(
        "/plan-city-day",
        params={
            "city": "上海",
            "date": "2026-05-23",
            "budgettotalcny": "500",
            "peoplecount": "2",
            "mode": "low_budget",
            "candidateplacescandidateplaces": "上海博物馆,豫园,外滩,武康路",
            "travelerpreferences": '[{"name":"A","likes":["拍照"],"constraints":["少走路"]}]',
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert [stop["name"] for stop in body["route"]][:2] == ["上海博物馆", "豫园"]
    assert body["mode"] == "low_budget"


def test_plan_city_day_accepts_coze_traveler_preference_dict_shape():
    response = client.post(
        "/plan-city-day?candidateplacescandidateplaces=上海博物馆,豫园,外滩,武康路"
        '&travelerpreferences={"A":["拍照","美食","少走路"],"B":["博物馆","高性价比"]}',
        json={
            "city": "上海",
            "date": "2026-05-23",
            "budgettotalcny": "500",
            "peoplecount": "2",
            "mode": "low_budget",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["route"]
    assert "少走路" in body["conflict_resolution"]


def test_low_energy_mode_reduces_overloaded_day_and_warns_about_feasibility():
    response = client.post(
        "/plan-city-day",
        json=sample_payload(
            mode="low_energy",
            end_time="16:30",
            candidate_places=["上海博物馆", "豫园", "外滩", "武康路", "新天地", "田子坊"],
        ),
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["route"]) <= 3
    assert body["feasibility"]["status"] == "adjusted"
    assert any("低体力" in warning for warning in body["feasibility"]["warnings"])


def test_tight_budget_switches_to_low_cost_recommendations():
    response = client.post(
        "/plan-city-day",
        json=sample_payload(mode="low_budget", budget_total_cny=160, people_count=2),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["budget_ledger"]["risk"] in {"tight", "over"}
    assert body["food_recommendations"]
    assert body["food_recommendations"][0]["avg_price_cny"] <= 50
    assert "低预算" in body["conflict_resolution"]


def test_plan_b_replans_after_weather_event_and_preserves_completed_places():
    initial = client.post("/plan-city-day", json=sample_payload()).json()

    response = client.post(
        "/plan-b",
        json={
            "original_request": sample_payload(),
            "current_plan": initial,
            "event": "突然下雨，而且大家有点累，想保留外滩但减少步行",
            "completed_places": ["上海博物馆"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan_b_reason"]
    assert body["route"][0]["name"] == "上海博物馆"
    assert body["mode"] == "low_energy"
    assert any("雨" in warning for warning in body["feasibility"]["warnings"])


def test_trip_review_returns_profile_update_and_next_trip_optimizations():
    response = client.post(
        "/trip-review",
        json={
            "previous_profile": {"pace": "balanced", "food": ["本帮菜"]},
            "trip_summary": "外滩夜景很喜欢，但下午走太多路，预算最后还剩80元。",
            "liked_places": ["外滩", "上海博物馆"],
            "pain_points": ["步行太多"],
            "actual_spend_cny": 420,
            "budget_total_cny": 500,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["updated_profile"]["pace"] == "low_energy"
    assert "夜景" in body["updated_profile"]["likes"]
    assert body["next_trip_optimizations"]
