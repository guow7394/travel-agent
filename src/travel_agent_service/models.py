import json
from datetime import date as date_type
from typing import Any, Dict, List, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


PlanningMode = Literal["balanced", "low_budget", "low_energy", "special_forces"]


def _parse_string_list(value: str) -> List[str]:
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        loaded = None

    if isinstance(loaded, list):
        return [str(item).strip() for item in loaded if str(item).strip()]

    normalized = value
    for separator in ("，", "、", ";", "\n"):
        normalized = normalized.replace(separator, ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _coerce_preference_dict(value: Dict[str, Any]) -> List[Dict[str, Any]]:
    if {"name", "likes", "constraints"} & set(value.keys()):
        return [value]

    travelers = []
    constraint_keywords = ("少走", "不想", "不能", "禁忌", "过敏", "无障碍")
    for name, preferences in value.items():
        items = preferences
        if isinstance(preferences, str):
            items = _parse_string_list(preferences)
        if not isinstance(items, list):
            items = [preferences]
        normalized_items = [str(item).strip() for item in items if str(item).strip()]
        constraints = [item for item in normalized_items if any(keyword in item for keyword in constraint_keywords)]
        likes = [item for item in normalized_items if item not in constraints]
        travelers.append({"name": str(name), "likes": likes, "constraints": constraints})
    return travelers


class TravelerPreference(BaseModel):
    name: str
    likes: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)


class PlanCityDayRequest(BaseModel):
    city: str
    date: str = Field(default_factory=lambda: date_type.today().isoformat())
    start_time: str = Field(default="09:30", validation_alias=AliasChoices("start_time", "starttime"))
    end_time: str = Field(default="20:00", validation_alias=AliasChoices("end_time", "endtime"))
    budget_total_cny: int = Field(default=500, gt=0, validation_alias=AliasChoices("budget_total_cny", "budgettotalcny"))
    people_count: int = Field(default=2, gt=0, validation_alias=AliasChoices("people_count", "peoplecount"))
    mode: PlanningMode = "balanced"
    start_place: str = Field(default="人民广场", validation_alias=AliasChoices("start_place", "startplace"))
    end_place: str = Field(default="人民广场", validation_alias=AliasChoices("end_place", "endplace"))
    candidate_places: List[str] = Field(
        default_factory=lambda: ["上海博物馆", "豫园", "外滩", "武康路"],
        min_length=1,
        max_length=12,
        validation_alias=AliasChoices(
            "candidate_places",
            "candidateplaces",
            "candidateplacescandidateplaces",
        ),
    )
    traveler_preferences: List[TravelerPreference] = Field(
        default_factory=list,
        validation_alias=AliasChoices("traveler_preferences", "travelerpreferences"),
    )
    public_base_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("public_base_url", "publicbaseurl"),
    )

    @field_validator("candidate_places", mode="before")
    @classmethod
    def parse_candidate_places(cls, value):
        if isinstance(value, str):
            return _parse_string_list(value)
        return value

    @field_validator("traveler_preferences", mode="before")
    @classmethod
    def parse_traveler_preferences(cls, value):
        if value in (None, ""):
            return []
        if isinstance(value, str):
            try:
                loaded = json.loads(value)
            except json.JSONDecodeError:
                return [{"name": "traveler", "likes": _parse_string_list(value), "constraints": []}]
            if isinstance(loaded, dict):
                return _coerce_preference_dict(loaded)
            return loaded
        if isinstance(value, dict):
            return _coerce_preference_dict(value)
        return value


class Location(BaseModel):
    longitude: float
    latitude: float


class Place(BaseModel):
    name: str
    location: Location
    category: str = "sight"
    ticket_cny: int = 0
    default_stay_minutes: int = 75
    indoor_score: float = 0.5
    tags: List[str] = Field(default_factory=list)


class RouteStop(BaseModel):
    name: str
    arrival: str
    stay_minutes: int
    location: Location
    note: str


class RouteLeg(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_place: str = Field(alias="from")
    to_place: str = Field(alias="to")
    distance_m: int
    duration_min: int
    transport: Literal["walk", "metro", "taxi"]


class FoodRecommendation(BaseModel):
    name: str
    near_stop: str
    avg_price_cny: int
    location: Location
    reason: str


class BudgetLedger(BaseModel):
    planned_total: int
    remaining: int
    risk: Literal["ok", "tight", "over"]
    breakdown: Dict[str, int]


class Feasibility(BaseModel):
    status: Literal["ok", "adjusted", "infeasible"]
    warnings: List[str] = Field(default_factory=list)


class PlanCityDayResponse(BaseModel):
    route: List[RouteStop]
    legs: List[RouteLeg]
    food_recommendations: List[FoodRecommendation]
    budget_ledger: BudgetLedger
    feasibility: Feasibility
    conflict_resolution: str
    static_map_url: str
    mocked: bool
    action_card_markdown: str
    mode: PlanningMode
    plan_b_reason: Optional[str] = None


class PlanBRequest(BaseModel):
    original_request: PlanCityDayRequest
    current_plan: Dict[str, Any]
    event: str
    completed_places: List[str] = Field(default_factory=list)


class TripReviewRequest(BaseModel):
    previous_profile: Dict[str, Any] = Field(default_factory=dict)
    trip_summary: str
    liked_places: List[str] = Field(default_factory=list)
    pain_points: List[str] = Field(default_factory=list)
    actual_spend_cny: int = Field(ge=0)
    budget_total_cny: int = Field(gt=0)


class TripReviewResponse(BaseModel):
    updated_profile: Dict[str, Any]
    next_trip_optimizations: List[str]
    budget_learning: str
    memory_write_suggestion: Dict[str, Any]
