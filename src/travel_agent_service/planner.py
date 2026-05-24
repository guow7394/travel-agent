import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Sequence, Tuple

from .amap import AmapClient
from .cards import render_action_card
from .mock_data import SHANGHAI_FOOD, SHANGHAI_PLACES
from .models import (
    BudgetLedger,
    Feasibility,
    FoodRecommendation,
    Location,
    Place,
    PlanCityDayRequest,
    PlanCityDayResponse,
    RouteLeg,
    RouteStop,
)
from .static_map import build_static_map_url, expanded_route_distance_meters


@dataclass
class ModePolicy:
    max_stops: int
    stay_multiplier: float
    prefer_low_cost: bool
    low_walking: bool
    buffer_minutes: int


MODE_POLICIES = {
    "balanced": ModePolicy(4, 1.0, False, False, 15),
    "low_budget": ModePolicy(4, 0.95, True, False, 10),
    "low_energy": ModePolicy(3, 0.85, False, True, 25),
    "special_forces": ModePolicy(6, 0.65, False, False, 5),
}


def plan_city_day(request: PlanCityDayRequest) -> PlanCityDayResponse:
    amap = AmapClient()
    live_distance = _live_distance_enabled()
    policy = MODE_POLICIES[request.mode]
    warnings: List[str] = []
    used_live_geocoding = False

    start = _resolve_place(request.start_place, request.city, amap)
    end = _resolve_place(request.end_place, request.city, amap)
    candidates = [_resolve_place(name, request.city, amap) for name in request.candidate_places]
    if any("高德地理编码" in place.tags for place in candidates + [start, end]):
        used_live_geocoding = True

    ordered_places = _order_places(start, candidates)
    if len(ordered_places) > policy.max_stops:
        reason = _mode_name(request.mode)
        warnings.append(f"{reason}下候选地点过多，已优先保留最顺路的 {policy.max_stops} 个。")
        ordered_places = ordered_places[: policy.max_stops]

    route, legs, schedule_warnings, used_live_routes = _build_schedule(
        request, start, end, ordered_places, policy, amap
    )
    warnings.extend(schedule_warnings)
    if amap.enabled and live_distance and not used_live_routes:
        warnings.append("高德路径规划暂不可用，已自动切换为估算距离和耗时。")

    food, used_live_food = _choose_food(request, route, amap)
    budget = _build_budget(request, route, legs, food)
    if budget.risk == "over":
        warnings.append("预算存在超支风险，建议现场减少打车或替换为更低客单价餐厅。")
    elif budget.risk == "tight":
        warnings.append("预算余量较小，建议把临时购物和加餐作为可选项。")

    status = "ok" if not warnings else "adjusted"
    feasibility = Feasibility(status=status, warnings=warnings)
    static_map_url = build_static_map_url(
        route=route,
        start_location=start.location,
        end_location=end.location,
        amap_key=amap.key,
        public_base_url=request.public_base_url,
    )
    mocked = not (used_live_geocoding or used_live_routes or used_live_food)
    response = PlanCityDayResponse(
        route=route,
        legs=legs,
        food_recommendations=food,
        budget_ledger=budget,
        feasibility=feasibility,
        conflict_resolution=_conflict_resolution(request, budget),
        static_map_url=static_map_url,
        mocked=mocked,
        action_card_markdown="",
        mode=request.mode,
    )
    response.action_card_markdown = render_action_card(response)
    return response


def replan_for_plan_b(
    request: PlanCityDayRequest,
    event: str,
    completed_places: Sequence[str],
) -> PlanCityDayResponse:
    lowered = event.lower()
    new_mode = request.mode
    if any(keyword in event for keyword in ["累", "少走", "下雨", "雨"]) or "tired" in lowered:
        new_mode = "low_energy"
    elif any(keyword in event for keyword in ["省钱", "预算", "太贵"]) or "budget" in lowered:
        new_mode = "low_budget"

    remaining = [place for place in request.candidate_places if place not in completed_places]
    if "外滩" in request.candidate_places and "外滩" not in remaining and "外滩" not in completed_places:
        remaining.append("外滩")
    revised_request = request.model_copy(update={"mode": new_mode, "candidate_places": remaining})
    plan = plan_city_day(revised_request)

    if completed_places:
        completed_stops = []
        for name in completed_places:
            place = _resolve_place(name, request.city, AmapClient())
            completed_stops.append(
                RouteStop(
                    name=place.name,
                    arrival="已完成",
                    stay_minutes=0,
                    location=place.location,
                    note="已完成，PlanB 保留该节点。",
                )
            )
        plan.route = completed_stops + [stop for stop in plan.route if stop.name not in completed_places]

    plan.mode = new_mode
    plan.plan_b_reason = f"根据突发情况“{event}”，保留已完成行程并改用{_mode_name(new_mode)}。"
    if any(keyword in event for keyword in ["下雨", "雨"]):
        plan.feasibility.warnings.append("检测到下雨风险，优先减少露天停留并增加室内/打车选项。")
        plan.feasibility.status = "adjusted"
    plan.action_card_markdown = render_action_card(plan)
    return plan


def _resolve_place(name: str, city: str, amap: AmapClient) -> Place:
    if city == "上海" and name in SHANGHAI_PLACES:
        return SHANGHAI_PLACES[name]
    geocoded = amap.geocode(name, city)
    if geocoded:
        return geocoded
    fallback = SHANGHAI_PLACES.get(name)
    if fallback:
        return fallback
    return Place(
        name=name,
        location=Location(longitude=121.473701, latitude=31.230416),
        default_stay_minutes=60,
        tags=["mock"],
    )


def _order_places(start: Place, places: Sequence[Place]) -> List[Place]:
    remaining = list(places)
    ordered = []
    current = start
    while remaining:
        nearest = min(
            remaining,
            key=lambda place: expanded_route_distance_meters(current.location, place.location),
        )
        ordered.append(nearest)
        remaining.remove(nearest)
        current = nearest
    return ordered


def _build_schedule(
    request: PlanCityDayRequest,
    start: Place,
    end: Place,
    ordered_places: Sequence[Place],
    policy: ModePolicy,
    amap: AmapClient,
):
    route: List[RouteStop] = []
    legs: List[RouteLeg] = []
    warnings: List[str] = []
    used_live_routes = False
    current_time = _parse_time(request.start_time)
    end_limit = _parse_time(request.end_time)
    itinerary_places = [start, *ordered_places, end]
    measured_legs = _measure_itinerary_legs(itinerary_places, policy, amap, request.city)

    for index, place in enumerate(ordered_places):
        current_place = itinerary_places[index]
        distance_m, duration_min, transport, used_live_route = measured_legs[index]
        used_live_routes = used_live_routes or used_live_route
        current_time += duration_min
        stay_minutes = max(35, round(place.default_stay_minutes * policy.stay_multiplier))
        route.append(
            RouteStop(
                name=place.name,
                arrival=_format_time(current_time),
                stay_minutes=stay_minutes,
                location=place.location,
                note=_stop_note(place, request.mode),
            )
        )
        legs.append(
            RouteLeg(
                from_place=current_place.name,
                to_place=place.name,
                distance_m=distance_m,
                duration_min=duration_min,
                transport=transport,
            )
        )
        current_time += stay_minutes + policy.buffer_minutes

    current_place = itinerary_places[-2]
    distance_m, duration_min, transport, used_live_route = measured_legs[-1]
    used_live_routes = used_live_routes or used_live_route
    legs.append(
        RouteLeg(
            from_place=current_place.name,
            to_place=end.name,
            distance_m=distance_m,
            duration_min=duration_min,
            transport=transport,
        )
    )
    if current_time + duration_min > end_limit:
        warnings.append("当前地点数量和停留时长接近时间上限，建议把最后一个点作为可选项。")
    if request.mode == "low_energy":
        warnings.append("低体力模式已减少地点密度，并优先使用少步行交通。")
    return route, legs, warnings, used_live_routes


def _measure_itinerary_legs(
    places: Sequence[Place],
    policy: ModePolicy,
    amap: AmapClient,
    city: str,
) -> List[Tuple[int, int, str, bool]]:
    leg_pairs = list(zip(places, places[1:]))
    if not leg_pairs:
        return []
    if not (_live_distance_enabled() and amap.enabled):
        return [
            _measure_leg(origin.location, destination.location, policy, amap, city)
            for origin, destination in leg_pairs
        ]

    max_workers = min(len(leg_pairs), int(os.getenv("TRAVEL_AGENT_MAX_ROUTE_WORKERS", "6")))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(
            executor.map(
                lambda pair: _measure_leg(pair[0].location, pair[1].location, policy, amap, city),
                leg_pairs,
            )
        )


def _measure_leg(
    origin: Location,
    destination: Location,
    policy: ModePolicy,
    amap: AmapClient,
    city: str,
) -> Tuple[int, int, str, bool]:
    rough_distance_m = expanded_route_distance_meters(origin, destination)
    transport = _choose_transport(rough_distance_m, policy)
    if _live_distance_enabled():
        route = amap.route(origin, destination, transport, city)
        if route:
            return route.distance_m, route.duration_min, transport, True
        measured = amap.distance(origin, destination)
        if measured:
            distance_m, duration_min = measured
            return distance_m, duration_min or _estimated_leg_duration(distance_m, transport), transport, True
    return rough_distance_m, _estimated_leg_duration(rough_distance_m, transport), transport, False


def _choose_transport(distance_m: int, policy: ModePolicy):
    if distance_m <= 900 and not policy.low_walking:
        return "walk"
    if policy.prefer_low_cost:
        return "walk" if distance_m <= 1600 else "metro"
    if policy.low_walking and distance_m > 700:
        return "taxi"
    if distance_m <= 1800:
        return "walk"
    return "metro"


def _estimated_leg_duration(distance_m: int, transport: str):
    if transport == "walk":
        return max(4, round(distance_m / 75))
    if transport == "metro":
        return max(12, round(distance_m / 260) + 8)
    return max(8, round(distance_m / 360) + 5)


def _choose_food(
    request: PlanCityDayRequest,
    route: Sequence[RouteStop],
    amap: AmapClient,
) -> Tuple[List[FoodRecommendation], bool]:
    per_person_budget = request.budget_total_cny / max(request.people_count, 1)
    lunch_stop = _lunch_stop(route)
    if _live_distance_enabled() and amap.enabled and lunch_stop:
        live_options = amap.search_food_near(
            lunch_stop.location,
            near_stop=lunch_stop.name,
            city=request.city,
            per_person_budget=per_person_budget,
        )
        live_options = _rank_food_options(live_options, request.mode, per_person_budget)
        if live_options:
            return live_options[:2], True

    route_names = {stop.name for stop in route}
    options = [
        food
        for food in SHANGHAI_FOOD
        if food.near_stop in route_names or food.near_stop in {request.start_place, request.end_place}
    ] or SHANGHAI_FOOD
    options = _rank_food_options(options, request.mode, per_person_budget)
    return options[:2], False


def _rank_food_options(
    options: Sequence[FoodRecommendation],
    mode: str,
    per_person_budget: float,
) -> List[FoodRecommendation]:
    if mode == "low_budget" or per_person_budget < 120:
        return sorted(options, key=lambda food: food.avg_price_cny)
    return sorted(
        options,
        key=lambda food: (food.avg_price_cny > per_person_budget * 0.55, food.avg_price_cny),
    )


def _lunch_stop(route: Sequence[RouteStop]):
    if not route:
        return None
    for stop in route:
        arrival_minutes = _parse_time(stop.arrival)
        if 11 * 60 <= arrival_minutes <= 14 * 60:
            return stop
    return route[min(1, len(route) - 1)]


def _build_budget(
    request: PlanCityDayRequest,
    route: Sequence[RouteStop],
    legs: Sequence[RouteLeg],
    food: Sequence[FoodRecommendation],
) -> BudgetLedger:
    tickets = sum(_ticket_for(stop.name) for stop in route) * request.people_count
    transport = sum(_leg_cost(leg) for leg in legs) * request.people_count
    meal = (food[0].avg_price_cny if food else 45) * request.people_count
    planned_total = tickets + transport + meal
    remaining = request.budget_total_cny - planned_total
    if remaining < 0:
        risk = "over"
    elif remaining <= request.budget_total_cny * 0.2:
        risk = "tight"
    else:
        risk = "ok"
    return BudgetLedger(
        planned_total=planned_total,
        remaining=remaining,
        risk=risk,
        breakdown={"tickets": tickets, "transport": transport, "meal": meal},
    )


def _ticket_for(name: str) -> int:
    return SHANGHAI_PLACES.get(name, Place(name=name, location=Location(longitude=0, latitude=0))).ticket_cny


def _leg_cost(leg: RouteLeg) -> int:
    if leg.transport == "walk":
        return 0
    if leg.transport == "metro":
        return 5
    return max(16, round(leg.distance_m / 1000 * 4))


def _conflict_resolution(request: PlanCityDayRequest, budget: BudgetLedger) -> str:
    constraints = "、".join(
        constraint
        for traveler in request.traveler_preferences
        for constraint in traveler.constraints
    )
    likes = "、".join(like for traveler in request.traveler_preferences for like in traveler.likes)
    mode_text = _mode_name(request.mode)
    if request.mode == "low_budget":
        return f"低预算优先：在满足{constraints or '基础约束'}的前提下，保留{likes or '核心兴趣'}，餐饮和交通都选低成本方案。"
    if request.mode == "low_energy":
        return f"低体力优先：把{constraints or '少步行'}作为硬约束，保留最顺路且代表性最高的地点。"
    if budget.risk != "ok":
        return f"预算是硬约束，已压缩交通和餐饮弹性；若现场加项，优先牺牲购物和咖啡休息。"
    return f"{mode_text}下保留博物馆、拍照和美食偏好；少走路作为硬约束，地点顺序按距离折中。"


def _stop_note(place: Place, mode: str) -> str:
    if mode == "low_energy":
        return "控制停留节奏，必要时直接打车到下一站。"
    if mode == "special_forces":
        return "快进快出，抓核心体验。"
    if "拍照" in place.tags:
        return "适合拍照打卡，注意别压缩后续交通时间。"
    return "按计划停留即可。"


def _mode_name(mode: str) -> str:
    return {
        "balanced": "均衡模式",
        "low_budget": "低预算模式",
        "low_energy": "低体力模式",
        "special_forces": "特种兵模式",
    }[mode]


def _live_distance_enabled() -> bool:
    return os.getenv("TRAVEL_AGENT_LIVE_DISTANCE", "").lower() in {"1", "true", "yes", "on"}


def _parse_time(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def _format_time(minutes: int) -> str:
    hour = minutes // 60
    minute = minutes % 60
    return f"{hour:02d}:{minute:02d}"
